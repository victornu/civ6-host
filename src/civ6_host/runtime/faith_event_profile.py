"""XP1 FaithChanged facade ABI; the retained shared lease remains authoritative."""
from functools import lru_cache
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source

SOURCE=('work/host-extensions/xp1-production-placement-static/faith-source-supplement-v1.json',
        '78fc77f6f21625fa3da666b402abf39f19b52a982d7ac012bb214ffb83ca2ce9')
EVENT_KIND=0xb3495127
TABLES={'outer':(0x8a8df0,{8:0x1843b0,0xb8:0x4bd1a0}),
        'player':(0x8aa2c8,{8:0x4c6a80,0xe0:0x4c7270}),
        'facade':(0x8aa8a8,{8:0x4c9830,0x10:0x4c9930,0x18:0x4c98f0})}
OPS={'get_player':('outer',0xb8),'release_context':('outer',8),'release_player':('player',8),
     'get_facade':('player',0xe0),'release_facade':('facade',8),'get_slot18':('facade',0x18),'get_slot10':('facade',0x10)}

@lru_cache(maxsize=2)
def verify_source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import source
        from .native import native_event_b3495127 as shared
        p=source()
        if EVENT_KIND not in {int(kind,16) for kind in p['callbacks']}:
            raise ValueError('XP2 FaithChanged producer is absent')
        shared.verify_source_evidence()
        return p
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown FaithChanged source engine')
    from .native import native_event_b3495127 as shared
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-faith-changed.static.v1' or p['image']['sha256']!=XP1_CORE_SHA256
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or (p['event_kind'],p['record_type'],p['record_size'])!=(EVENT_KIND,194,96)
            or p['validation']!=dict(all_instruction_bytes_match_image=True,selected_native_operations=7)):
        raise ValueError('XP1 FaithChanged source changed')
    tables={name:(v[0],{int(k):t for k,t in v[1].items()}) for name,v in p['tables'].items()}
    if tables!=TABLES:raise ValueError('XP1 FaithChanged native table changed')
    checks={'0x1843b0':{'ret 0'},'0x4c7270':{'jmp 0x1804c96d0','jmp 0x1804c9700'},
            '0x4c96d0':{'mov qword ptr [rcx + 8], rdx','mov dword ptr [rcx + 0x18], 1'},
            '0x4c9700':{'mov qword ptr [rcx + 0x10], rdx','mov dword ptr [rcx + 0x18], 1'},
            '0x4c98f0':{'mov dword ptr [rdx], eax','call 0x18009c480'},
            '0x4c9930':{'call 0x180296220','call 0x1800a1a80'}}
    for name,expected in checks.items():
        if not expected<={r['text'] for r in p['functions'][name]['instructions']}:
            raise ValueError('XP1 FaithChanged wrapper layout changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    shared.verify_source_evidence();return p

def select_tables(core_sha256,retained):
    if core_sha256==BASE_CORE_SHA256:return retained
    if core_sha256==XP2_CORE_SHA256:
        proof=verify_source(core_sha256=core_sha256)
        selected=proof['faith_query_abi']['tables']
        if set(retained)!=set(selected):raise ValueError('FaithChanged shared table seam changed')
        result={}
        for name,(_,slots) in retained.items():
            if set(slots)!=set(int(slot,16) for slot in selected[name]['slots']):
                raise ValueError('XP2 FaithChanged table slot set changed')
            result[name]=(int(selected[name]['vtable_rva'],16),
                          {int(slot,16):int(target,16) for slot,target in selected[name]['slots'].items()})
        return result
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified FaithChanged engine')
    verify_source(core_sha256=core_sha256)
    if set(retained)!=set(TABLES) or any(set(v[1])!=set(TABLES[n][1]) for n,v in retained.items()):
        raise ValueError('FaithChanged shared table seam changed')
    return TABLES

def select_specs(core_sha256,retained):
    if core_sha256==BASE_CORE_SHA256:return retained
    if core_sha256==XP2_CORE_SHA256:
        proof=verify_source(core_sha256=core_sha256)
        operations=proof['faith_query_abi']['operations']
        if set(retained)!=set(OPS) or set(retained)!=set(operations):
            raise ValueError('XP2 FaithChanged native operation seam changed')
        return {name:(int(operations[name]['target_rva'],16),result,args)
                for name,(_,result,args) in retained.items()}
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified FaithChanged engine')
    verify_source(core_sha256=core_sha256)
    if set(retained)!=set(OPS):raise ValueError('FaithChanged native operation seam changed')
    return {name:(TABLES[OPS[name][0]][1][OPS[name][1]],result,args) for name,(_,result,args) in retained.items()}

def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import source_dependencies
        return source_dependencies()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown FaithChanged source engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=verify_source()
    return {str(resolve_path(resource_root()/r['path']).resolve()):r['sha256']
            for r in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['shared_source'],*p['references'])}

def bind_owner(backend,core,read,*,core_sha256=XP1_CORE_SHA256):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256!=core_sha256:
        raise ValueError('FaithChanged has a foreign native owner')
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import bind_owner as bind_xp2
        bind_xp2(backend,core,read)
        verify_source(core_sha256=core_sha256)
        from .native.native_deferred_empty_profile import _ROWS
        if _ROWS[194]['record_sizes']!={96}:
            raise ValueError('XP2 FaithChanged empty receiver changed')
        return SOURCE[1]
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown FaithChanged owner engine')
    from .xp1_status_profiles import _instruction_spans
    p=verify_source()
    for rva,raw in _instruction_spans(p):
        if read(core._handle+rva,len(raw))!=raw:raise ValueError('XP1 FaithChanged code changed')
    for table,slots in TABLES.values():
        for slot,target in slots.items():
            if read(core._handle+table+slot,8)!=(core._handle+target).to_bytes(8,'little'):
                raise ValueError('XP1 FaithChanged table changed')
    from .native.native_deferred_empty_profile import _ROWS
    actual=_ROWS[194]
    if any((tuple(sorted(actual[k]))!=tuple(v) if k=='record_sizes' else actual[k]!=v) for k,v in p['receiver_row'].items()):
        raise ValueError('FaithChanged empty receiver changed')
    return SOURCE[1]
