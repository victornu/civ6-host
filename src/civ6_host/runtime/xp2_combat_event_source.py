"""XP2 source selection for shared combat, experience and world-text transport.

The original native map clone, command query and F8 release posthook retain
their ownership. This profile grants no actor attack action or gameplay rule.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source, _body

SOURCE = ('work/host-extensions/xp2-combat-events-static/source-profile-v2.json',
          '951ff441db51dc18ce568dcd4ed354dbb26185c1c91235b414760b70000cd9e5')
KINDS = frozenset((0x8256dbe1, 0xa479f83f, 0x45b517d6))
_PREDICATE = dict(game_table=0xa10ee8, slot=0x130, target=0x5976c0,
                  state_getter=0x306b80, state_global=0xb8e140)
_METHODS = dict(get_service=0x5904c0, release_outer=0x8972d0, map_ctor=0x99e4b0,
                map_dtor=0x99e5d0, map_lookup=0x99f5c0, query=0x5a2a40, release_service=0x5a2a70)
_SLOTS = ((0xa101e8, 0xe0, 0x5904c0), (0xa101e8, 8, 0x8972d0),
          (0xa12a00, 0x10, 0x5a2a40), (0xa12a00, 8, 0x5a2a70),
          (0xabf080, 0x60, 0x99f5c0))
_MAP_NAMES = {'map_constructor': 'promotion_map_constructor', 'map_assign': 'map_assign',
              'map_copy': 'map_copy', 'map_destructor': 'promotion_map_destructor',
              'variant_clone_construct': 'variant_clone_construct',
              'variant_clone_assign': 'variant_clone_assign', 'variant_release': 'variant_release'}
_LIST_NAMES = ('modifier_list_constructor', 'modifier_list_copy', 'modifier_list_copy_storage',
               'modifier_list_cleanup', 'modifier_list_destructor', 'modifier_list_deleting_destructor')
_MODIFIER_KEYS = frozenset((0x240b41bc, 0x3e03e415, 0x3c8e1717, 0xb064dc49, 0xb3ac66b4,
                            0x41370dd6, 0xdf5078d4, 0x6839883c, 0xac8b21a7, 0x46421e43))
_CHILD_SCALARS = frozenset((0x730c22a7, 0xa544d916, 0xc6d9cb06, 0x6d8dcc3e, 0x0786c210,
                           0xb223c62d, 0x4292e3cf, 0xd385cd83, 0xb4b611cf, 0xaf6eeeff,
                           0x0e13c019, 0x32d7cbf4))


def rows(value):
    return tuple(row for fragment in _body(value)['fragments'] for row in fragment['instructions'])


def _texts(p, name):
    return {row['text'] for row in rows(p['functions'][name])}


def _verify(p):
    from .native import native_event_argument_tree as tree, native_event_a479f83f as experience
    from .native import native_combat_receiver as receiver, native_event_45b517d6 as world
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if (p['schema'] != 'civ6-host.xp2-combat-events.source.v2'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256'] != XP2_CORE_SHA256
            or p['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or dict(p['predicate']) != _PREDICATE
            or set(p['contract']['kinds']) != KINDS
            or any(p['validation'][name] is not True for name in (
                'all_instruction_bytes_match_image', 'all_virtual_targets_match_image',
                'all_conditional_targets_captured', 'complete_release_alternate_branch',
                'all_existing_ownership_primitive_bodies_reused'))):
        raise ValueError('XP2 combat source identity changed')
    for ref in p['references'].values():
        _source((ref['path'], ref['sha256'])) if ref['path'].endswith('.json') else None
    original = tree.verify_source_evidence()
    experience.verify_source_evidence(); receiver.verify_source_evidence()
    world.verify_source_evidence(); world.verify_city_source()
    if (p['root_fields'] != original['contract']['root_builder']['fields']
            or {kind: EXE_EVENT_CALLBACKS.get(kind) for kind in KINDS} !=
               {0x8256dbe1: 0x142fe0, 0xa479f83f: 0x1561b0, 0x45b517d6: 0x15a300}):
        raise ValueError('XP2 combat registered callback or root fields changed')
    keys = lambda body: {int(m.group(1), 16) for r in rows(body)
                         if (m := re.fullmatch(r'mov edx, 0x([0-9a-f]+)', r['text']))}
    if (keys(p['functions']['root_builder']) != {int(row['key'], 16) for row in p['root_fields']}
            or keys(p['functions']['child_builder']) !=
               keys(original['captures']['child_map_builder']) | {0x46421e43}
            or p['contract']['required_child_fields'] != 14
            or p['contract']['child_modifier_lists_admitted'] is not True
            or frozenset(p['contract']['modifier_list_keys']) != _MODIFIER_KEYS
            or dict(p['contract']['modifier_list_variant']) != dict(
                tag=11, width=0, nonnull_flags=0x11000000, null_flags=0, native_list_vtable=0xabfb80)
            or p['contract']['administrative_snapshot_complete'] is not False
            or p['validation']['modifier_list_clone_and_release_bodies_closed'] is not True
            or p['contract']['combat_map_release_posthook_required'] is not True
            or p['contract']['native_map_deep_copy_required'] is not True):
        raise ValueError('XP2 combat root/child ownership envelope changed')
    for name, value in p['functions'].items():
        body = value['body']; captured = rows(value)
        raw = b''.join(bytes.fromhex(row['bytes']) for row in captured)
        starts = {int(row['va'], 16) for row in captured}
        if (len(raw) != body['total_length'] or hashlib.sha256(raw).hexdigest() != body['code_sha256']
                or int(body['start_va'], 16) != 0x180000000 + int(value['rva'], 16)):
            raise ValueError('XP2 combat selected function bytes changed: ' + name)
        for fragment in body['fragments']:
            cursor = int(fragment['start_va'], 16)
            for row in fragment['instructions']:
                if int(row['va'], 16) != cursor:
                    raise ValueError('XP2 combat function has an instruction gap')
                cursor += len(bytes.fromhex(row['bytes']))
        if any(row['text'].startswith('j') and not row['text'].startswith('jmp ')
               and int(row['text'].split()[-1], 16) not in starts for row in captured):
            raise ValueError('XP2 combat conditional source path is incomplete')
    promotion = p['promotion']
    if (dict(promotion['methods']) != _METHODS or tuple(map(tuple, promotion['slots'])) != _SLOTS
            or (promotion['outer_table'], promotion['service_table'], promotion['map_table']) !=
               (0xa101e8, 0xa12a00, 0xabf080)
            or (promotion['command'], promotion['result_key'], promotion['native_query_implementation']) !=
               (0xb4edd43f, 0x315247e7, 0xd0140)):
        raise ValueError('XP2 promotion query ABI changed')
    required = {
        'root': {'call 0x18007c670', 'jmp qword ptr [rax + 0xa0]'},
        'combat_caller': {'mov ecx, 0x8256dbe1', 'call 0x180163c40', 'call 0x1805fa8b0'},
        'child_builder': {'mov edx, 0x46421e43', 'cmp dword ptr [rax + 0x10], 9', 'call 0x1805fd5a0'},
        'predicate': {'call 0x180306b80', 'mov ecx, dword ptr [rax + 0x2dac]', 'cmp ecx, 0x3e8'},
        'promotion_service_query': {'jmp 0x1800d0140'},
        'promotion_service_release': {'jmp 0x18058ff80', 'dec eax', 'mov dword ptr [rcx + 8], eax', 'ret'},
        'promotion_implementation': {'call qword ptr [rax + 0x40]', 'call qword ptr [rax + 0x38]',
                                    'call qword ptr [r10 + 0x90]', 'call qword ptr [r10 + 0x48]'},
        'experience_caller': {'mov dword ptr [rbp - 0x59], 0xa479f83f', 'call 0x1805fb000',
                              'mov dword ptr [rbp + 0x77], 0x45b517d6', 'call 0x1805fb270'},
        'experience_builder': {'mov edx, 0xf0548bb7', 'mov edx, 0xa1e5a149', 'mov r8d, 0x400',
                               'call 0x18007c670', 'call qword ptr [rax + 0xa0]'},
        'world_builder': {'mov edx, 0xf0548bb7', 'mov edx, 0x23739f42', 'mov edx, 0xa1e5a149',
                          'mov edx, 0x8c468e3c', 'mov edx, 0xc4d568d1', 'call 0x1809a6e40',
                          'call 0x18007c670', 'call qword ptr [rax + 0xa0]', 'call 0x18099e5d0'},
        'world_string_setter': {'mov r8d, 5', 'lea ecx, [rax + 1]', 'mov dword ptr [rsp + 0x28], ecx',
                               'mov dword ptr [rsp + 0x20], 1', 'mov dword ptr [rsp + 0x30], 0x1000000'},
        'modifier_append': {'cmp word ptr [rax], 0xb', 'call 0x1809a7740', 'call 0x1809a7970'},
        'modifier_list_setter': {'mov dword ptr [rbx], 0xb', 'mov edx, 0x11000000', 'mov qword ptr [rbx + 8], rbp'},
        'modifier_string_append': {'lea edx, [r9 + 4]', 'mov r9d, 1', 'call 0x1809a79e0'},
        'variant_clone_assign': {'cmp cx, 0xb', 'call 0x1809a7740', 'call 0x1809a7c00',
                                'mov dword ptr [rbx + 0x14], 0x11000000'},
        'variant_release': {'cmp ax, 0xb', 'call qword ptr [rax]'},
        'modifier_list_cleanup': {'call 0x1809a1560', 'add rbx, 0x18'},
    }
    for name, expected in required.items():
        if not expected <= _texts(p, name):
            raise ValueError('XP2 combat native caller/helper join changed: ' + name)
    state = rows(p['functions']['state_getter'])
    if len(state) != 2 or tuple(state[0]['rip_targets']) != ('0x180b8e140',) or state[1]['text'] != 'ret':
        raise ValueError('XP2 combat native state getter changed')
    w = p['world_text']
    if ((w['event_kind'], w['callback_rva'], w['record_type'], w['record_size']) !=
            (0x45b517d6, 0x15a300, 250, 368)
            or tuple(w['descriptor_keys']) != (0xf0548bb7, 0x23739f42)
            or (w['selector_tag'], w['position_tag'], w['text_tag'], w['descriptor_tag'], w['descriptor_bytes']) !=
               (3, 0, 5, 1024, 8) or w['nonempty_text_only'] is not True):
        raise ValueError('XP2 world-text envelope changed')
    return p


@lru_cache(maxsize=1)
def source():
    return _verify(_source(SOURCE))


def verify_source(core_sha256=XP2_CORE_SHA256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Expected exact XP2 combat source')
    return source()


def ensure_source(core_sha256):
    verify_source(core_sha256)


def source_sha(core_sha256, retained):
    verify_source(core_sha256)
    return SOURCE[1]


def source_dependencies(*, execution_image=None):
    from .a0_family_source import verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp2_configuration_profile import source_dependencies as configuration
    from .xp2_unit_orders_source import source_dependencies as orders
    from .xp1_visibility_cache_gate import source_dependencies as cache
    p = source(); pins = {}
    for dependencies in (configuration(), orders(execution_image=execution_image),
                         cache(core_sha256=XP2_CORE_SHA256, execution_image=execution_image)):
        for path, digest in dependencies.items():
            key = str(Path(path).resolve())
            if key in pins and pins[key] != digest:
                raise ValueError('Conflicting XP2 combat source dependency')
            pins[key] = digest
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), *p['references'].values()]
    if execution_image is None:
        refs.append(p['image'])
    for ref in refs:
        key = str(resolve_path(resource_root() / ref['path']).resolve())
        if key in pins and pins[key] != ref['sha256']:
            raise ValueError('Conflicting XP2 combat source dependency')
        pins[key] = ref['sha256']
    if execution_image is not None:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins = materialize_runtime_source_pins(
            pins, execution_image=execution_image, provenance_images=(p['image'],))
    verify_pinned_files(pins)
    return pins


def core_fragments():
    for value in source()['functions'].values():
        for fragment in _body(value)['fragments']:
            yield int(fragment['start_va'], 16) - 0x180000000, b''.join(
                bytes.fromhex(row['bytes']) for row in fragment['instructions'])


def verify_live(base, read):
    if type(base) is not int or not 0 < base < (1 << 47) - 0x1000000 or not callable(read):
        raise ValueError('XP2 combat requires exact native module and reader')
    count = 0
    for rva, raw in core_fragments():
        for offset in range(0, len(raw), 4096):
            chunk = raw[offset:offset + 4096]
            if read(base + rva + offset, len(chunk)) != chunk:
                raise ValueError('XP2 combat live code changed at ' + hex(rva + offset))
            count += 1
    for table, slot, target in source()['slots']:
        if read(base + table + slot, 8) != struct.pack('<Q', base + target):
            raise ValueError('XP2 combat native virtual target changed')
        count += 1
    return count


@dataclass(frozen=True)
class BoundCombatSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    unit_query_source_receipt: object
    guarded_read_spans: int


def bind_owner(backend, core, read, *, execution_image=None):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 combat source has a foreign native owner')
    from .xp2_unit_orders_source import bind_owner as bind_query_manager
    if execution_image is None:
        execution_image = getattr(core, '_civ6_host_execution_image', None)
    source_dependencies(execution_image=execution_image)
    query_receipt = bind_query_manager(backend, core, read)
    prior = getattr(backend, '_xp2_combat_source', None)
    if prior is not None:
        if (type(prior) is not BoundCombatSource or prior.owner is not backend or prior.core is not core
                or prior.base != core._handle or prior.source_sha256 != SOURCE[1]
                or prior.unit_query_source_receipt is not query_receipt):
            raise ValueError('XP2 combat bound source belongs to another lifetime')
        return source()
    receipt = BoundCombatSource(backend, core, core._handle, SOURCE[1], query_receipt,
                               verify_live(core._handle, read))
    backend._xp2_combat_source = receipt
    return source()


def predicate_selection(core_sha256, retained, proof):
    p = verify_source(core_sha256)
    selected = dict(core_captures=dict(game_owner_predicate=_body(p['functions']['predicate'])),
                    leaves=dict(core_game_state_getter=dict(raw_hex=b''.join(bytes.fromhex(row['bytes'])
                        for row in rows(p['functions']['state_getter'])).hex())))
    return (_PREDICATE['game_table'], _PREDICATE['target'], _PREDICATE['state_getter'],
            _PREDICATE['state_global'], selected)


@dataclass(frozen=True)
class PromotionLayout:
    methods: object
    slots: tuple
    map_table: int
    outer_table: int
    service_table: int


def promotion_layout(core_sha256, methods, slots):
    verify_source(core_sha256)
    if set(methods) != set(_METHODS):
        raise ValueError('XP2 promotion query operation set changed')
    selected = {name: (_METHODS[name], result, args) for name, (_, result, args) in methods.items()}
    return PromotionLayout(selected, _SLOTS, 0xabf080, 0xa101e8, 0xa12a00)


def promotion_proof(core_sha256, retained):
    p = verify_source(core_sha256)
    aliases = dict(outer_e0='promotion_outer_e0', outer_release='promotion_outer_release',
        map_constructor='promotion_map_constructor', map_destructor='promotion_map_destructor',
        map_lookup='promotion_map_lookup', service_query='promotion_service_query', service_release='promotion_service_release')
    selected = {}
    for name, key in aliases.items():
        body = _body(p['functions'][key]); body['start_va'] = body['fragments'][0]['start_va']
        selected[name] = body
    return dict(core_functions=selected)


def map_owner_source(core_sha256=XP2_CORE_SHA256):
    p = verify_source(core_sha256)
    from .combat_map_profiles import OWNER_SOURCE
    base = _source(OWNER_SOURCE)
    registry = base['contract']['registry']
    if (registry['initial_next_id'] != 1 or registry['node_size'] != 32 or registry['sentinel_offset'] != 8
            or registry['node_fields']['0x14'] != 'refcountDWORD'
            or registry['node_fields']['0x18'] != 'owned map pointer'):
        raise ValueError('Shared combat native-map registry contract changed')
    aliases = {**_MAP_NAMES, **{name: name for name in _LIST_NAMES}}
    return dict(core_captures={name: _body(p['functions'][key]) for name, key in aliases.items()},
                source_sha256=SOURCE[1], registry_source_sha256=OWNER_SOURCE[1],
                core_sha256=core_sha256, contract=dict(registry=registry))


def verify_map_live(base, read, *, core_sha256=XP2_CORE_SHA256):
    proof = map_owner_source(core_sha256)
    for name, body in proof['core_captures'].items():
        for fragment in body['fragments']:
            raw = b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions'])
            rva = int(fragment['start_va'], 16) - 0x180000000
            for offset in range(0, len(raw), 4096):
                chunk = raw[offset:offset + 4096]
                if read(base + rva + offset, len(chunk)) != chunk:
                    raise ValueError('XP2 combat native map primitive changed: ' + name)
    for slot, target in ((0x1d0, 0x99e6c0), (0x178, 0x99e9d0)):
        if read(base + 0xabf080 + slot, 8) != struct.pack('<Q', base + target):
            raise ValueError('XP2 combat native map virtual primitive changed')
    if read(base + 0xabfb80, 8) != struct.pack('<Q', base + 0x9a7840):
        raise ValueError('XP2 combat native modifier-list destructor changed')


def validate_child_fields(core_sha256, values, scalar_keys):
    """Validate transport envelopes without decoding the native modifier strings.

    The complete original root map is copied by NativeCombatMapOwner before
    this descriptor extraction and stays alive until its F8 release posthook.
    Borrowed list addresses never become administrative result values.
    """
    verify_source(core_sha256)
    mandatory = _CHILD_SCALARS | {0x57c6ed30, 0x95f2cf6e}
    if frozenset(scalar_keys) != _CHILD_SCALARS or not mandatory <= set(values) <= mandatory | _MODIFIER_KEYS:
        raise ValueError('XP2 combat child fields differ from source-selected scalar/list envelope')
    from .native.native_application_mirror import decode_scalar
    for key in _CHILD_SCALARS:
        decode_scalar(values[key], 2)
    for key in set(values) - mandatory:
        raw = values[key]
        if type(raw) is not bytes or len(raw) != 24:
            raise ValueError('XP2 combat modifier list has an incomplete variant')
        tag = struct.unpack_from('<H', raw)[0]
        pointer, width, flags = struct.unpack_from('<QII', raw, 8)
        if tag != 11 or width != 0 or flags != (0x11000000 if pointer else 0):
            raise ValueError('XP2 combat modifier list differs from native tag11 ownership envelope')


def administrative_snapshot_policy(core_sha256):
    p = verify_source(core_sha256)
    return dict(administrative_snapshot_policy=p['contract']['administrative_snapshot_policy'],
                administrative_snapshot_complete=False, native_modifier_lists_preserved=True,
                modifier_values_decoded=False)


def world_text_source():
    return source()['world_text']


def cache_snapshot(owner):
    from .a0_foundation_events import require_borrow
    from .xp1_visibility_cache_gate import require_internal_cache
    continuation = require_borrow(owner)
    if continuation.owner.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 world-text has a foreign continuation')
    require_internal_cache(continuation)
    raw = continuation.publisher.cache_map_snapshot
    if type(raw) is not bytes or len(raw) != 28:
        raise ValueError('XP2 world-text requires its actual populated map snapshot')
    return raw
