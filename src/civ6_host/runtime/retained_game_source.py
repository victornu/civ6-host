"""Exact engine profiles for the borrowed native Game cache getter."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,_source,_body
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE=('work/host-extensions/retained-game-static/retained-game-xp1-source-v1.json',
        'af5a1035c67dde734ac4514effa40756999fd3658e5780956c644683961f3a51')


@dataclass(frozen=True)
class RetainedGameABI:
    facade_vtable_rva:int
    owner_vtable_rva:int
    getter_slot:int
    getter_rva:int
    getter_length:int
    getter_sha256:str
    factory_rva:int
    release_rva:int


def getter_abi(core_sha256):
    if core_sha256==BASE_CORE_SHA256:
        return RetainedGameABI(0x79ECD8,0x766A70,0x128,0x434B00,28,
            '2210e968337657725a73dad2d9c5e0d7f0423e2521a3dfa1f291b3e51579a989',0x42DCD0,0x434750)
    if core_sha256==XP2_CORE_SHA256:
        p=source(core_sha256=core_sha256)['profile']
        return RetainedGameABI(p['game_facade_vtable_rva'],p['ownership']['owner_vtable_rva'],
            0x128,p['getter_rva'],p['getter_length'],p['getter_code_sha256'],0x58FFA0,0x596DD0)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified retained Game engine')
    p=source()['profile']
    return RetainedGameABI(0x8A9A88,0x867788,0x128,0x4C3B30,28,p['getter_code_sha256'],0x4BCDD0,0x4C3790)


def source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown retained Game source engine')
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.retained_game_xp1.static.v1'
            or p['profile']['core_sha256']!=XP1_CORE_SHA256
            or p['profile']['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or p['validation']['all_instruction_bytes_match_pinned_images'] is not True
            or p['validation']['native_execution'] is not False):
        raise ValueError('Retained Game source identity differs')
    a=p['profile'];expected={'outer_vtable_rva':0x8A8DF0,'inner_vtable_rva':0x8D7168,
        'game_facade_vtable_rva':0x8A9A88,'cache_owner_vtable_rva':0x867788,'cache_service_vtable_rva':0x8D7238,
        'factory_rva':0x4BCDD0,'getter_rva':0x4C3B30,'release_rva':0x4C3790,'getter_slot':0x128,
        'service_global_rva':0x9F22E0,'inner_global_rva':0x9F2620,'game_global_rva':0x9F2628}
    if any(int(a[k],16)!=v for k,v in expected.items()) or a['getter_length']!=28 or a['getter_code_sha256']!='ae19d931d3439fece717c116a2e82ed80c7ec309a85570e15202b8ce168e12b0':
        raise ValueError('Retained Game native ABI differs')
    layout={'facade_size':32,'facade_live_game':8,'facade_cache_owner':16,'facade_refcount':24,
            'outer_inner':8,'inner_game':96,'inner_cache_service':0x1A68,'service_cache_owner':8,
            'cache_owner_service':32,'cache_owner_snapshot_value':0x16F8}
    if any(a['layout'][k]!=v for k,v in layout.items()):raise ValueError('Retained Game layout differs')
    for ref in p['references'].values():_source((ref['path'],ref['sha256']))
    return p


def body(name):
    p=source();route=p['profile']['live_body_sources'][name]
    if route['kind']=='local_body':
        value=p
        for key in route['selector']:value=value[key]
        return _body(value)
    if route['kind']!='referenced_body':raise ValueError('Unknown retained Game body source')
    row=p['referenced_bodies'][route['key']];ref=p['references'][row['reference']]
    value=_source((ref['path'],ref['sha256']))
    for key in row['selector']:value=value[key]
    value=_body(value)
    raw=b''.join(bytes.fromhex(i['bytes']) for f in value['fragments'] for i in f['instructions'])
    if hashlib.sha256(raw).hexdigest()!=row['instruction_bytes_sha256']:
        raise ValueError('Retained Game referenced body differs')
    return value


def _q(read,address):
    raw=read(address,8)
    if type(raw) is not bytes or len(raw)!=8:raise ValueError('Incomplete retained Game memory read')
    return struct.unpack('<Q',raw)[0]


def context_state(base,context,read,*,core_sha256=XP1_CORE_SHA256):
    p=source(core_sha256=core_sha256);q=lambda a:_q(read,a)
    if core_sha256==XP2_CORE_SHA256:
        a=p['profile'];o=a['ownership']
        outer,inner_vt,inner_global=a['outer_vtable_rva'],a['inner_vtable_rva'],o['inner_global_rva']
        service_global,service_vt,owner_vt,game_global=o['service_global_rva'],o['service_vtable_rva'],o['owner_vtable_rva'],o['game_global_rva']
    else:
        outer,inner_vt,inner_global=0x8A8DF0,0x8D7168,0x9F2620
        service_global,service_vt,owner_vt,game_global=0x9F22E0,0x8D7238,0x867788,0x9F2628
    if not context or q(context)!=base+outer:raise ValueError('Retained Game outer context differs')
    inner=q(context+8)
    if not inner or inner!=q(base+inner_global) or q(inner)!=base+inner_vt:
        raise ValueError('Retained Game inner context differs')
    service=q(inner+0x1A68)
    if not service or service!=q(base+service_global) or q(service)!=base+service_vt:
        raise ValueError('Retained Game service unavailable or replaced')
    owner=q(service+8)
    if not owner or q(owner)!=base+owner_vt or q(owner+0x20)!=service:
        raise ValueError('Retained Game native cache owner unavailable or replaced')
    game=q(inner+0x60)
    if not game or game!=q(base+game_global):raise ValueError('Retained Game live identity differs')
    return dict(inner=inner,service=service,owner=owner,game=game)


def verify_live(base,context,read,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import verify_live as selected,SOURCE as selected_source
        selected(base,read)
        return dict(source_sha256=selected_source[1],native_identity=context_state(base,context,read,core_sha256=core_sha256),population_qualified=False)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown retained Game live engine')
    names=('factory','getter','release','facade_constructor','service_owner_dispatch','service_owner_getter',
        'service_getter','service_constructor','service_factory','service_ensure_owner','owner_factory',
        'owner_constructor','owner_initialize','owner_initialize_members','member_constructor',
        'allocation_thunk','allocate_facade','free_facade','prepare','inner_destroy','cache_service_clear')
    for name in names:
        for f in body(name)['fragments']:
            for i in f['instructions']:
                raw=bytes.fromhex(i['bytes'])
                if read(base+int(i['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('Retained Game instructions differ: '+name)
    for vt,slot,target in ((0x8A8DF0,0xA0,0x4BCDD0),(0x8A9A88,0x128,0x4C3B30),(0x8A9A88,8,0x4C3790)):
        if _q(read,base+vt+slot)!=base+target:raise ValueError('Retained Game virtual slot differs')
    state=context_state(base,context,read)
    return dict(source_sha256=SOURCE[1],native_identity=state,population_qualified=False)


def verify_status_live(base,read,*,host_pointer,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_preload_source import verify_bodies,SOURCE as selected_source
        verify_bodies(base,read,('status_c0','status_c0_extended','event_suppressed','session_getter','session_flag'))
        if _q(read,base+0xB8AA80)!=host_pointer:raise ValueError('C0 host owner differs')
        return dict(source_sha256=selected_source[1],c0_wrappers_verified=True,saved_game_loaded=False)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown retained status engine')
    from .event_argument_source import _verify_bodies
    source()
    _verify_bodies(base,read,('status_c0','status_c0_extended','event_suppressed','session_getter','session_flag'))
    if _q(read,base+0x9F2640)!=host_pointer:raise ValueError('C0 host owner differs')
    return dict(source_sha256=SOURCE[1],c0_wrappers_verified=True,saved_game_loaded=False)


def source_pins(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source_dependencies
        return source_dependencies()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown retained Game source engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source();refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},*p['references'].values()]
    return {str(resolve_path(resource_root()/r['path'])):r['sha256'] for r in refs}
