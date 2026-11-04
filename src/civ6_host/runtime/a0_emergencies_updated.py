"""Exact XP1 EmergenciesUpdated A0 producer in the existing deferred FIFO.

The Core has already updated its emergency cache before this notification.
This transport does not query or replace that cache, and does not admit gameplay.
"""
from dataclasses import dataclass
from types import MappingProxyType
import hashlib
import struct
from .configuration_profiles import _source,_body,XP1_CORE_SHA256
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE=('work/host-extensions/xp1-publication-events-static/emergencies-updated-source-v1.json',
        '2c96bef7e1c9ca5ed6b2cd9234c7d1b543f2ede5b30155e4869d16e5e3f901fd')
EVENT_KIND=0x281D81D2
RECORD_TYPE=0x127
SELECTOR=0xA1E5A149
EXE_SHA='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'

def instructions(body):return [r for f in _body(body)['fragments'] for r in f['instructions']]

def source():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p=_source(SOURCE);f=p['functions'];r=p['receiver']
    if (p['schema']!='civ6_host.xp1_publication_event_review.static.v1' or p['native_execution'] is not False
        or p['images']['xp1']['sha256']!=XP1_CORE_SHA256 or p['images']['exe']['sha256']!=EXE_SHA
        or EXE_EVENT_CALLBACKS.get(EVENT_KIND)!=0x145950
        or p['registration']['callback_va']!='0x140145950'
        or r['record_type']!=RECORD_TYPE or r['event_name']!='GameCoreEvent::EmergenciesUpdated'
        or int(r['row_static_va'],16)-int(r['table_base'],16)!=RECORD_TYPE*48
        or r['handler']['start_va']!='0x1400d5a70'
        or p['validation']['instruction_bytes_match'] is not True):
        raise ValueError('EmergenciesUpdated source/profile changed')
    for ref in p['references'].values():_source((ref['path'],ref['sha256']))
    expected={
        'callback_thunk':('jmp 0x14014d0d0',),
        'callback':('mov dword ptr [rsp + 0x30], 0','call 0x1401232d0','call 0x1409898c0'),
        'writer':('mov dword ptr [rbx], 0x60','mov dword ptr [rbx + 4], 0x127',
                  'lock xadd dword ptr [rsi + 0x38], edi','mov dword ptr [rbx + 8], edi',
                  'mov qword ptr [rax], rcx','mov dword ptr [rax], edi'),
        'normalizer':('call rax','xor eax, eax'),
        'xp1_emitter':('mov edx, 0xa1e5a149','call 0x180845fb0','call 0x180070b10',
                       'call qword ptr [rax + 0xa0]','call 0x180844580'),
        'xp1_map_setter':('mov dword ptr [rsp + 0x30], 3','mov dword ptr [rsp + 0x38], r8d'),
    }
    for key,required in expected.items():
        texts=[x['text'] for x in instructions(f[key])]
        if any(t not in texts for t in required):raise ValueError('EmergenciesUpdated ABI source changed: '+key)
    producer=[x['text'] for x in instructions(p['producers']['0x76020'])]
    if 'mov qword ptr [rsp + 0x20], 0x281d81d2' not in producer or producer[-1]!='jmp 0x180517a60':
        raise ValueError('EmergenciesUpdated XP1 caller differs')
    calls=[x['text'] for x in instructions(r['handler']) if x['text'].startswith('call ')]
    if calls!=['call 0x14098a780','call 0x1400dc0d0','call 0x14098a7b0']:
        raise ValueError('EmergenciesUpdated receiver has unreviewed side effects')
    setup=[x['text'] for x in instructions(r['setup'])]
    for text in ('mov qword ptr [rcx], rbx','mov qword ptr [rcx + 8], rbx',
                 'mov qword ptr [rcx + 0x10], rbx','mov qword ptr [rcx + 0x18], rdx',
                 'mov dword ptr [rax + 0x20], ebx','and byte ptr [rax + 0x30], 0xfc'):
        if text not in setup:raise ValueError('EmergenciesUpdated empty receiver initialization differs')
    return p

def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values()]
    result={str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source_dependencies as selected
        result.update(selected())
    elif core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown publication event engine')
    return result

def receiver_rows(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Unknown publication receiver engine')
    p=source();r=p['receiver'];raw=b''.join(bytes.fromhex(x['bytes']) for x in instructions(r['handler']))
    return {RECORD_TYPE:dict(record_sizes=[0x60],event_name=r['event_name'],
        handler_va=r['handler']['start_va'],handler_body_sha256=hashlib.sha256(raw).hexdigest(),
        source_sha256=SOURCE[1])}

@dataclass(frozen=True)
class PublicationEventProfile:
    record_types_by_kind: object
    record_sizes: object
    source_sha256: str

def enable(service,publication):
    from .xp1_cache_publication import SavedCachePublication
    from .xp1_postload_candidate import FINISHED_STAGE
    service._check()
    if type(publication) is not SavedCachePublication:
        raise ValueError('Publication events require the actual saved publication attempt')
    b=publication.owner
    if (service.publication_event_profile is not None or service.active_kind is not None
        or service.arguments.depth or service.pending or service.deferred._draining_empty_receivers
        or b.prefix.event_arguments is not service.arguments or b.prefix.deferred_events is not service.deferred
        or b.core is not service.deferred.core or b.context!=service.deferred.context
        or b._xp1_publication_attempt is not publication or publication.native_attempted
        or b.stage!=FINISHED_STAGE or b.busy or b.poisoned or b.destroyed
        or service.host_notification_counter or service.host_metadata_counter):
        raise ValueError('Publication events need their idle original loaded owner')
    p=source();base=b.core._handle;core_sha256=b.load_abi.core_sha256
    if service.deferred.cache_core_sha256!=core_sha256:raise ValueError('Publication event engine owner differs')
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source as selected,SOURCE as selected_source
        native=selected();bodies=[]
        for name in ('event_producer','event_emitter','event_map_setter','internal_event_dispatch','event_suppressed','session_getter','session_flag','map_constructor','map_destructor'):
            fn=native['functions'][name]
            bodies.extend((fn['body'],*(t['body'] for t in fn['out_of_line_tail_jumps'])))
        source_sha256=selected_source[1]
    elif core_sha256==XP1_CORE_SHA256:
        bodies=(*p['producers'].values(),p['functions']['xp1_emitter'],p['functions']['xp1_map_setter'])
        source_sha256=SOURCE[1]
    else:raise ValueError('Unknown publication event engine')
    for body in bodies:
        for row in instructions(body):
            raw=bytes.fromhex(row['bytes'])
            rva=int(row['rva'],16) if 'rva' in row else int(row['va'],16)-0x180000000
            if b.runtime.read(base+rva,len(raw))!=raw:
                raise ValueError('Live EmergenciesUpdated emitter changed')
    profile=PublicationEventProfile(MappingProxyType({EVENT_KIND:frozenset((RECORD_TYPE,))}),
                                   MappingProxyType({RECORD_TYPE:0x60}),source_sha256)
    service.publication_event_profile=service._publication_event_profile=profile
    return service

def encode(kind,fields,sequence,*,normalizer_transform_present,optional_callback_present,queue_metadata_service):
    if (type(kind) is not int or kind!=EVENT_KIND or type(fields) is not dict or set(fields)!={SELECTOR}
        or normalizer_transform_present is not False or optional_callback_present is not False
        or queue_metadata_service is not None):
        raise ValueError('Unqualified EmergenciesUpdated kind, fields or optional host services')
    raw=fields[SELECTOR]
    if (type(raw) is not bytes or len(raw)!=24 or struct.unpack_from('<H',raw)[0]!=3
        or struct.unpack_from('<I',raw,8)[0]!=0 or struct.unpack_from('<I',raw,20)[0]!=0):
        raise ValueError('EmergenciesUpdated requires the copied native selector-zero variant')
    if type(sequence) is not int or not 1<=sequence<=0xffffffff:raise ValueError('Invalid publication event sequence')
    record=bytearray(0x60)
    struct.pack_into('<4I',record,0,0x60,RECORD_TYPE,sequence,0)
    struct.pack_into('<ii',record,16,-1,-1)
    for offset in (24,32,40,48,56):struct.pack_into('<HHi',record,offset,0xffff,0,-1)
    struct.pack_into('<QI',record,64,0,0)
    struct.pack_into('<I',record,80,sequence)
    # Writer copies an 8-byte local after only DWORD +0 was initialized, then
    # overwrites that DWORD with sequence. +84..87 is unused stack padding;
    # zeroing is restricted to the existing no-hook/no-subscriber profile.
    return bytes(record)

def dispatch(service,kind,fields):
    profile=service.publication_event_profile
    if type(profile) is not PublicationEventProfile or profile is not service._publication_event_profile:
        raise ValueError('Publication event profile replaced')
    record=encode(kind,fields,service._sequence+1,normalizer_transform_present=service.normalizer_transform_present,
                  optional_callback_present=False,queue_metadata_service=None)
    service._enqueue(record)
    service.emit('native_deferred_host_event_enqueued',dispatch_kind=hex(kind),queue_type=hex(RECORD_TYPE),
        event_name='GameCoreEvent::EmergenciesUpdated',record_hex=record.hex(),pending_count=len(service.pending),
        source_sha256=profile.source_sha256,copied_variant_headers=True,pointer_payloads_retained=False,
        unused_stack_padding_policy='zero only under explicit empty receiver profile',
        native_queries_executed=False,cache_gate_modified=False,consumer_validated=False,
        native_dispatch_return=0,eligible_for_training=False)
    return 0
