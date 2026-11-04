"""XP1 source selection for the unchanged GoodyHutReward shared producer."""
from functools import lru_cache
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,BASE_CORE_SHA256,_source

SOURCE=('work/host-extensions/xp1-goody-hut-static/source-v1.json',
        'e1ba9ca5bc96f1d29244af720ed2a737c745af7ff27b76295dd6ed2ea10b76b4')
EVENT_KIND=0xc08fc0f9


def _rows(body):
    return body.get('instructions') or tuple(r for part in body['fragments'] for r in part['instructions'])


@lru_cache(maxsize=2)
def verify_source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import source
        from . import goody_hut_reward as shared
        shared.verify_source(core_sha256=BASE_CORE_SHA256)
        proof=source()
        if EVENT_KIND not in {int(kind,16) for kind in proof['callbacks']}:
            raise ValueError('XP2 GoodyHutReward producer is absent')
        return proof
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown GoodyHutReward source engine')
    from . import goody_hut_reward as shared
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-goody-hut-reward.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256']!=XP1_CORE_SHA256
            or (p['event_kind'],p['record_type'],p['record_size'])!=(EVENT_KIND,259,112)
            or EXE_EVENT_CALLBACKS.get(EVENT_KIND)!=0x1480e0
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or p['references'][0]['sha256']!=shared.CORE_PROOF_SHA256
            or p['references'][1]['sha256']!=shared.EXE_PROOF_SHA256):
        raise ValueError('XP1 GoodyHutReward source identity changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    builder=p['functions']['0x518a80'];rows=_rows(builder);texts={r['text'] for r in rows}
    required={'mov edx, 0xa1e5a149','mov edx, 0xd6fcf3e4','mov edx, 0xa1fbc372',
              'cmp ax, 1','mov edx, 0xf0548bb7','cmp ax, 2','mov edx, 0x23739f42',
              'mov dword ptr [rsp + 0x30], 0x1000000','mov dword ptr [rsp + 0x28], 1',
              'mov r8d, 0x400','mov dword ptr [rsp + 0x20], 8','call qword ptr [rax + 0xb0]',
              'call 0x180070b10','call qword ptr [rax + 0xa0]','call 0x180844580'}
    if not required<=texts:raise ValueError('XP1 reward descriptor/dispatch contract changed')
    targets={r['text']:int(r['va'],16) for r in rows if r['text'] in
             ('call 0x180070b10','call qword ptr [rax + 0xa0]','call 0x180844580')}
    if not targets['call 0x180070b10']<targets['call qword ptr [rax + 0xa0]']<targets['call 0x180844580']:
        raise ValueError('XP1 reward dispatch or descriptor lifetime changed')
    caller=_source((p['caller_reference']['path'],p['caller_reference']['sha256']))
    texts={r['text'] for r in _rows(caller)}
    if not {'mov dword ptr [rbp - 0x50], 0xc08fc0f9','mov dword ptr [rbp - 0x4c], 0',
            'mov word ptr [rsp + 0x20], ax','mov dword ptr [rsp + 0x24], eax',
            'mov word ptr [rsp + 0x22], si','call 0x180518a80'}<=texts:
        raise ValueError('XP1 reward caller changed')
    return p


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import source_dependencies
        return source_dependencies()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown GoodyHutReward source engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=verify_source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],
                           p['caller_reference'],*p['references']]
    return {str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}


def bind_owner(backend,core,read,*,core_sha256=XP1_CORE_SHA256):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256!=core_sha256:
        raise ValueError('XP1 reward has a foreign native owner')
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_event_source import bind_owner as bind_xp2, SOURCE as selected
        bind_xp2(backend,core,read)
        verify_source(core_sha256=core_sha256)
        from .native.native_deferred_empty_profile import resolve_empty_receiver_row
        from . import goody_hut_reward as shared
        if resolve_empty_receiver_row(259)!=shared.receiver_row():
            raise ValueError('XP2 GoodyHutReward shared receiver changed')
        return selected[1]
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown GoodyHutReward owner engine')
    p=verify_source();caller=_source((p['caller_reference']['path'],p['caller_reference']['sha256']))
    for body in (*p['functions'].values(),caller):
        for row in _rows(body):
            raw=bytes.fromhex(row['bytes'])
            if read(core._handle+int(row['va'],16)-0x180000000,len(raw))!=raw:
                raise ValueError('XP1 reward live source changed')
    from . import goody_hut_reward as shared
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    if resolve_empty_receiver_row(259)!=shared.receiver_row():raise ValueError('XP1 reward receiver differs')
    return SOURCE[1]
