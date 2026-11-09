"""XP1 WorldTextMessage admission over the existing shared EXE transport.

The native emitter owns gameplay and text formatting. This profile supplies
source identity and the real populated map snapshot; it computes neither.
"""
from functools import lru_cache
from types import MappingProxyType

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp1-world-text-static/source-v1.json',
          'ffbfc9e504eb6a6255f155f584fc37ace81b0a441561af4e262bcf91eec1bdcf')
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = 0x45B517D6, 250, 368


def _rows(body):
    return body.get('instructions') or tuple(
        row for fragment in body['fragments'] for row in fragment['instructions'])


@lru_cache(maxsize=2)
def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import world_text_source,verify_source as verify_xp2
        verify_xp2(core_sha256)
        world=world_text_source()
        if ((world['event_kind'],world['record_type'],world['record_size']) !=
                (EVENT_KIND,RECORD_TYPE,RECORD_SIZE) or world['nonempty_text_only'] is not True):
            raise ValueError('XP2 world-text event contract changed')
        return world
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('World-text source requires exact XP1 or XP2')
    from .native import native_event_45b517d6 as shared
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .event_argument_source import SOURCE as reader_source
    from .xp1_visibility_cache_gate import GATE_SOURCE
    p = _source(SOURCE)
    if (p['schema'] != 'civ6-host.xp1-world-text.static.v1'
            or p['native_execution'] is not False
            or p['image']['sha256'] != XP1_CORE_SHA256
            or p['exe_image']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or (p['event_kind'], p['record_type'], p['record_size']) !=
                (EVENT_KIND, RECORD_TYPE, RECORD_SIZE)
            or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 0x15A300
            or p['references']['exe_producer']['sha256'] != shared.PROOF_SHA256
            or p['references']['city_normalization']['sha256'] != shared.CITY_PROOF_SHA256
            or p['references']['event_reader']['sha256'] != reader_source[1]
            or p['references']['cache_gate']['sha256'] != GATE_SOURCE[1]
            or tuple(p['contract']['admitted_descriptor_keys']) != (0xF0548BB7, 0x23739F42)
            or p['contract']['nonempty_text_only'] is not True
            or p['validation']['all_selected_instruction_bytes_match_pinned_image'] is not True):
        raise ValueError('XP1 world-text source identity changed')
    refs = {name: _source((r['path'], r['sha256'])) for name, r in p['references'].items()}
    shared.verify_source_evidence(); shared.verify_city_source()
    rows = _rows(refs['builder']); texts = {r['text'] for r in rows}
    required = {'mov edx, 0xa1e5a149', 'mov edx, 0x8c468e3c', 'mov edx, 0xc4d568d1',
                'cmp ax, 1', 'mov edx, 0xf0548bb7', 'cmp ax, 2', 'mov edx, 0x23739f42',
                'mov r8d, 0x400', 'mov dword ptr [rsp + 0x20], 8',
                'mov dword ptr [rsp + 0x28], 1', 'mov dword ptr [rsp + 0x30], 0x1000000',
                'call qword ptr [rax + 0xb0]', 'call 0x18084d300', 'call 0x180845fb0'}
    if not required <= texts:
        raise ValueError('XP1 world-text borrowed envelopes changed')
    order = {r['text']: int(r['va'], 16) for r in rows}
    if not order['call 0x180070b10'] < order['call qword ptr [rax + 0xa0]'] < order['call 0x180844580']:
        raise ValueError('XP1 world-text internal dispatch or lifetime changed')
    setter = {r['text'] for r in _rows(refs['string_setter'])}
    if not {'mov r8d, 5', 'lea ecx, [rax + 1]', 'mov dword ptr [rsp + 0x28], ecx',
            'mov dword ptr [rsp + 0x20], 1', 'mov dword ptr [rsp + 0x30], 0x1000000'} <= setter:
        raise ValueError('XP1 world-text string envelope changed')
    caller = {r['text'] for r in _rows(refs['caller'])}
    if not {'mov dword ptr [rbp + 0x77], 0x45b517d6', 'call 0x180518320'} <= caller:
        raise ValueError('XP1 world-text caller changed')
    return p


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import source_dependencies as xp2_dependencies
        return xp2_dependencies(execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires XP2 world-text ABI')
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('World-text source dependencies require exact XP1 or XP2')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp1_visibility_cache_gate import source_dependencies as cache_sources
    p = verify_source()
    pins = cache_sources()
    for r in (dict(path=SOURCE[0], sha256=SOURCE[1]), p['image'], p['exe_image'], *p['references'].values()):
        path = str(resolve_path(resource_root()/r['path']).resolve())
        if path in pins and pins[path] != r['sha256']:
            raise ValueError('Conflicting world-text source dependency')
        pins[path] = r['sha256']
    return pins


def event_profile(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires XP2 world-text ABI')
    if execution_image is not None:
        from .execution_images import identity
        identity(execution_image)
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    verify_source(core_sha256)
    row = resolve_empty_receiver_row(RECORD_TYPE)
    if row['event_name'] != 'GameCoreEvent::WorldTextMessage' or set(row['record_sizes']) != {RECORD_SIZE}:
        raise ValueError('World-text empty receiver changed')
    source_sha=SOURCE[1]
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import SOURCE as xp2_source
        source_sha=xp2_source[1]
    return A0FamilyProfile(MappingProxyType({EVENT_KIND: frozenset((RECORD_TYPE,))}),
                           MappingProxyType({RECORD_TYPE: RECORD_SIZE}), source_sha)


def bind_owner(backend, core, read, *, execution_image=None):
    if backend.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import bind_owner as bind_xp2
        if backend.core is not core:
            raise ValueError('XP2 world-text has a foreign native owner')
        if execution_image is None:
            execution_image=getattr(core,'_civ6_host_execution_image',None)
        bind_xp2(backend,core,read,execution_image=execution_image)
        return event_profile(XP2_CORE_SHA256,execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires XP2 world-text ABI')
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256 != XP1_CORE_SHA256:
        raise ValueError('XP1 world-text has a foreign native owner')
    p = verify_source()
    for name in ('builder', 'caller', 'string_setter'):
        r = p['references'][name]
        for row in _rows(_source((r['path'], r['sha256']))):
            raw = bytes.fromhex(row['bytes'])
            if read(core._handle + int(row['va'], 16) - 0x180000000, len(raw)) != raw:
                raise ValueError('XP1 world-text live instructions changed')
    return event_profile(XP1_CORE_SHA256)


def cache_snapshot(owner):
    backend=owner._foundation_backend
    if backend is not None and backend.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_combat_event_source import cache_snapshot as xp2_cache_snapshot
        return xp2_cache_snapshot(owner)
    """Borrow the real cache copy only inside the current qualified producer."""
    from .a0_foundation_events import require_borrow
    from .xp1_visibility_cache_gate import require_internal_cache
    continuation = require_borrow(owner)
    require_internal_cache(continuation)
    raw = continuation.publisher.cache_map_snapshot
    if type(raw) is not bytes or len(raw) != 28:
        raise ValueError('XP1 world-text requires its actual populated map snapshot')
    return raw
