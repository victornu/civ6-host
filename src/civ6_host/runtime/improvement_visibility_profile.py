"""XP1 ImprovementVisibilityChanged, using the existing shared query families."""
from functools import lru_cache
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-production-placement-static/f391-source-supplement-v1.json',
        '5551188ded52f9141a122e7ae066a5a2c59bb5c1c31dee3a72e58cc813e60e46')
EVENT_KIND=0xf391d7b3

@lru_cache(maxsize=1)
def verify_source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import source
        from .native import native_event_f391d7b3 as shared
        p=source()
        if EVENT_KIND not in {int(kind,16) for kind in p['callbacks']}:
            raise ValueError('XP2 improvement visibility producer is absent')
        shared.verify_source_evidence();shared.verify_typed_position_evidence();shared.verify_scoped_source_evidence()
        return p
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown improvement visibility engine')
    from . import turn_unit_event_profile as units, foundation_facade_profiles as facades
    from .native import native_event_f391d7b3 as shared
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-improvement-visibility.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256']!=XP1_CORE_SHA256
            or (p['event_kind'],p['record_type'],p['record_size'])!=(EVENT_KIND,145,160)
            or tuple(p['query_profiles']['mandatory'])!=units.SOURCE
            or tuple(p['query_profiles']['secondary_and_optional'])!=facades.SOURCE
            or p['validation']!=dict(all_instruction_bytes_match_image=True,existing_query_profiles_reused=True)):
        raise ValueError('XP1 improvement visibility source identity changed')
    checks={'visibility_producer':{'mov dword ptr [rbp - 0x71], 0xf391d7b3','call 0x180517bd0'},
            'host_dispatch':{'call qword ptr [rax + 0xa0]'}}
    for name,required in checks.items():
        if not required<={r['text'] for r in p['functions'][name]['instructions']}:
            raise ValueError('XP1 improvement visibility dispatch source changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    shared.verify_source_evidence();shared.verify_typed_position_evidence();shared.verify_scoped_source_evidence()
    return p

def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import source_dependencies
        return source_dependencies()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown improvement visibility source engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .turn_unit_event_profile import source_dependencies as unit_sources
    p=verify_source();pins=dict(unit_sources())
    for r in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['shared_source'],*p['references']):
        path=str(resolve_path(resource_root()/r['path']).resolve())
        if path in pins and pins[path]!=r['sha256']:raise ValueError('Conflicting improvement visibility source')
        pins[path]=r['sha256']
    return pins

def verify_live(base,read,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import verify_live as verify_xp2
        return verify_xp2(base,read)['verified_fragments']
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown improvement visibility live engine')
    from .xp1_status_profiles import _instruction_spans
    from .turn_unit_event_profile import verify_live as unit_live
    count=unit_live(base,read)
    for rva,raw in _instruction_spans(verify_source()):
        if read(base+rva,len(raw))!=raw:raise ValueError('XP1 improvement visibility caller changed')
        count+=1
    return count

def bind_owner(backend,core,read,*,core_sha256=XP1_CORE_SHA256):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256!=core_sha256:
        raise ValueError('Improvement visibility has a foreign native owner')
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import bind_owner
        bind_owner(backend,core,read)
        verify_xp1_once(core,core._handle,read,resource_root(),core_sha256=core_sha256)
    elif core_sha256==XP1_CORE_SHA256:
        verify_live(core._handle,read,core_sha256=core_sha256)
        verify_xp1_once(core,core._handle,read,resource_root())
    else:raise ValueError('Unknown improvement visibility owner engine')
    from .native.native_deferred_empty_profile import _ROWS
    actual=_ROWS[145];expected=verify_source()['receiver_row']
    if any((tuple(sorted(actual[k]))!=tuple(v) if k=='record_sizes' else actual[k]!=v) for k,v in expected.items()):
        raise ValueError('Improvement visibility empty receiver changed')
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import SOURCE as selected
        return selected[1]
    return SOURCE[1]
