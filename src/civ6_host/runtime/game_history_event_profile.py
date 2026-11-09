"""Explicit XP1 history/era supplement to the closed shared scalar codecs.

No gameplay is reimplemented: these EXE callbacks copy two native values into
the existing FIFO. Only the reviewed empty host subscriber route is admitted.
"""
from functools import lru_cache
import hashlib
from types import MappingProxyType
from .configuration_profiles import XP1_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-production-placement-static/game-history-moment-source-v1.json',
        '14dc8c765623a71fcca15bf13a7e2d955745af041487af7b5b35fddd2624e0f4')
ERA_SOURCE=('work/host-extensions/xp1-production-placement-static/game-era-source-supplement-v1.json',
            'a70037a8abb102311919609409a4b90eb7526059906c28ae2a1f1b133dc8016b')
EXE_SHA='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
HISTORY_KIND=0x4710f1a4
ERA_KIND=0xf50673b7
EVENTS=MappingProxyType({HISTORY_KIND:(0x105,0,0x147300,0x11f6e0,0xc5e60,0xd4cf0),
                         ERA_KIND:(0x104,6,0x147200,0x11f4e0,0xc5da0,0xd4c90)})


def _texts(body):return [r['text'] for r in body['instructions']]


@lru_cache(maxsize=1)
def verify_source():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p=_source(SOURCE);era=_source(ERA_SOURCE)
    if (p['schema']!='civ6-host.xp1-game-history-moment.static.v1'
            or era['schema']!='civ6-host.xp1-game-era-scalar-supplement.static.v1'
            or p['native_execution'] is not False or era['native_execution'] is not False
            or p['process_memory_read'] is not False or era['process_memory_read'] is not False
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256 or era['image']['sha256']!=XP1_CORE_SHA256
            or p['images']['exe']['sha256']!=EXE_SHA or era['history_reference']['sha256']!=SOURCE[1]
            or (p['event_kind'],p['record_type'],p['record_size'])!=(HISTORY_KIND,0x105,96)
            or (era['event_kind'],era['record_type'],era['record_size'])!=(ERA_KIND,0x104,96)
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or era['validation']['all_instruction_bytes_match_image'] is not True):
        raise ValueError('History/era scalar source identity changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    functions={HISTORY_KIND:p['functions']['exe'],ERA_KIND:p['neighbors'][0]['functions']}
    receiver=p['receiver']
    if (receiver['event_name']!='GameCoreEvent::GameHistoryMomentRecorded'
            or int(receiver['row_va'],16)-int(receiver['table_base'],16)!=0x105*48
            or receiver['initialized_state']!=dict(pre_hook=None,post_hook=None,row_plus10=None,
                state_pointer_nonnull=True,subscriber_count=0,subscriber_array=0,state_flag_mask3=0,
                subscriber_allocation_bytes=56)):
        raise ValueError('History receiver initialization identity changed')
    init=_texts(p['functions']['exe']['name_initializer'])
    if not {'call 0x1400c5da0','call 0x1400c5e60'}<=set(init):
        raise ValueError('History/era receiver name registration changed')
    for kind,(record,flag,callback,writer,setup,handler) in EVENTS.items():
        if EXE_EVENT_CALLBACKS.get(kind)!=callback:raise ValueError('History/era callback registry changed')
        f=functions[kind];cb=_texts(f[hex(callback)]);wr=_texts(f[hex(writer)])
        required={'cmp dword ptr [rdx], 0x6447c33d','mov eax, dword ptr [rdx + 0x50]',
                  'mov eax, dword ptr [rdx + 0x54]',f'call {hex(0x140000000+writer)}'}
        if not required<=set(cb):raise ValueError('History/era scalar callback changed')
        if ('mov dword ptr [rbp - 8], ecx' if flag==0 else 'mov dword ptr [rbp - 8], 6') not in cb:
            raise ValueError('History/era notification metadata changed')
        required={'mov dword ptr [rbx], 0x60',f'mov dword ptr [rbx + 4], {hex(record)}',
                  'mov dword ptr [rbx + 8], edi','mov dword ptr [rbx + 0xc], eax',
                  'movsd xmm0, qword ptr [r15]','movsd qword ptr [rax], xmm0',
                  'mov ecx, dword ptr [r15 + 8]','mov dword ptr [rax + 8], ecx','mov dword ptr [rax], edi',
                  'mov dword ptr [rcx + 0x34], esi','mov eax, dword ptr [r14 + 0x38]',
                  'mov dword ptr [rcx + 0x38], eax'}
        if not required<=set(wr):raise ValueError('History/era scalar writer changed')
        calls=[r for r in _texts(f[hex(handler)]) if r.startswith('call ')]
        if calls!=['call 0x14098a780','call 0x1400dc0d0','call 0x14098a7b0']:
            raise ValueError('History/era receiver has unreviewed effects')
        required={'xor ebx, ebx','lea ecx, [rbx + 0x38]','mov qword ptr [rcx], rbx',
                  'mov qword ptr [rcx + 8], rbx','mov qword ptr [rcx + 0x10], rbx',
                  'mov qword ptr [rcx + 0x18], rdx','mov qword ptr [rax + 8], rbx',
                  'mov dword ptr [rax + 0x20], ebx','and byte ptr [rax + 0x30], 0xfc'}
        if not required<=set(_texts(f[hex(setup)])):raise ValueError('History/era receiver setup changed')
    xp=p['functions']['xp1']
    if not {'mov edx, 0xa1e5a149','mov edx, 0xd6fcf3e4','mov edx, 0xa1fbc372',
            'call qword ptr [rax + 0xa0]'}<=set(_texts(xp['0x519650'])):
        raise ValueError('XP1 scalar emitter changed')
    for kind,body in ((HISTORY_KIND,xp['0x1be4b0']),(ERA_KIND,era['functions']['producer'])):
        text=_texts(body)
        if not any(hex(kind) in s for s in text) or 'call 0x180519650' not in text:
            raise ValueError('XP1 scalar caller changed')
    return p,era


def source_dependencies(*,execution_image=None):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p,era=verify_source()
    refs=[dict(path=path,sha256=sha) for path,sha in (SOURCE,ERA_SOURCE)]
    refs.extend((*p['references'],))
    pins={str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}
    if execution_image is None:
        pins.update({str(resolve_path(resource_root()/r['path']).resolve()):r['sha256']
                     for r in p['images'].values()})
    else:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins=materialize_runtime_source_pins(pins,execution_image=execution_image,
                                             provenance_images=p['images'].values())
    return pins


def receiver_rows():
    p,_=verify_source();fs={HISTORY_KIND:p['functions']['exe'],ERA_KIND:p['neighbors'][0]['functions']}
    names={HISTORY_KIND:'GameCoreEvent::GameHistoryMomentRecorded',ERA_KIND:'GameCoreEvent::GameEraChanged'}
    return {record:dict(record_sizes={96},event_name=names[kind],handler_va=hex(0x140000000+handler),
        handler_body_sha256=hashlib.sha256(b''.join(bytes.fromhex(r['bytes'])
            for r in fs[kind][hex(handler)]['instructions'])).hexdigest(),source_sha256=SOURCE[1] if kind==HISTORY_KIND else ERA_SOURCE[1])
        for kind,(record,_,_,_,_,handler) in EVENTS.items()}


def bind_owner(backend,core,read):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256!=XP1_CORE_SHA256:
        raise ValueError('History/era scalar owner mismatch')
    p,era=verify_source()
    # Immutable code is bound once to this exact Core owner before Load.
    for body in (*p['functions']['xp1'].values(),*era['functions'].values()):
        for r in body['instructions']:
            raw=bytes.fromhex(r['bytes'])
            if read(core._handle+int(r['va'],16)-0x180000000,len(raw))!=raw:
                raise ValueError('XP1 history/era live source changed')
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    if any(resolve_empty_receiver_row(k)!=v for k,v in receiver_rows().items()):
        raise ValueError('History/era receiver source differs')
    return ERA_SOURCE[1]
