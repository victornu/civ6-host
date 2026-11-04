"""Exact ABI/owner profiles for the existing cache-facade pipeline."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from types import MappingProxyType
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,_source,_body
from .saved_load_profiles import XP2_CORE_SHA256
from .a0_family_source import _path,verify_pinned_files,verify_extracted_sources

SOURCE=('work/host-extensions/cache-facade-static/cache-facade-xp1-source-v1.json',
        '0b3118d35d69098a3489adb0564bc1372a9dad4516344a8854d6991e2f0d9bb2')


@dataclass(frozen=True)
class CacheFacadeABI:
    core_sha256:str
    outer_vtable_rva:int
    game_facade_vtable_rva:int
    cache_service_vtable_rva:int
    system_facade_vtable_rva:int
    cache_b0_result_vtable_rva:int
    cache_c0_result_vtable_rva:int
    targets:object
    publish_rva:int
    copy_rva:int
    getter_rvas:frozenset
    release_rvas:frozenset
    full_refresh_admitted:bool


def facade_abi(core_sha256):
    if core_sha256==BASE_CORE_SHA256:
        from .native import native_ui_cache_facades as m
        return CacheFacadeABI(core_sha256,m.OUTER_VTABLE_RVA,m.GAME_FACADE_VTABLE_RVA,
            m.CACHE_SERVICE_VTABLE_RVA,m.SYSTEM_FACADE_VTABLE_RVA,
            m.CACHE_B0_RESULT_VTABLE_RVA,m.CACHE_C0_RESULT_VTABLE_RVA,
            MappingProxyType(dict(m.TARGET_RVAS)),0x434E30,0x436640,
            frozenset((0x42DCD0,0x42DD10,0x42DD90,0x436F10,0x4367C0)),
            frozenset((0x153060,0x434750,0x436460,0x43A9F0,0x437390,0x437080)),True)
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):raise ValueError('Unqualified cache-facade engine')
    p=source(core_sha256=core_sha256)['profile']
    return CacheFacadeABI(core_sha256,*(p[k] for k in ('outer_vtable_rva','game_facade_vtable_rva',
        'cache_service_vtable_rva','system_facade_vtable_rva','cache_b0_result_vtable_rva','cache_c0_result_vtable_rva')),
        MappingProxyType({(r['vtable_rva'],r['slot']):r['target_rva'] for r in p['targets']}),
        p['publish_rva'],p['copy_rva'],frozenset(p['getter_rvas']),frozenset(p['release_rvas']),False)


def source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown cache facade source engine')
    p=_source(SOURCE);a=p['profile']
    expected=dict(all_instruction_bytes_match_pinned_images=True,instruction_count=1790,
        equal_normalized_pairs=17,target_pair_count=13,native_execution=False,product_modified=False)
    if (p['schema']!='civ6_host.cache_facade_xp1.static.v1' or dict(p['validation'])!=expected
            or a['core_sha256']!=XP1_CORE_SHA256
            or a['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or a['full_refresh_admitted'] is not False or a['source_pins']!=p['source_pins']
            or tuple(a[k] for k in ('output_size','output_write_extent','output_canary_start','output_canary_size'))!=(32,28,28,4)
            or len(a['targets'])!=13 or set(a['getter_rvas'])!=set(a['factory_rvas'])):
        raise ValueError('Cache-facade source contract differs')
    return p


def source_pins(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source_dependencies
        return source_dependencies()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown cache facade source engine')
    p=source();refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},*p['references'].values(),*p['source_pins'].values()]
    return {str(_path(r['path'])):r['sha256'] for r in refs}


def body(name):
    p=source();route=p['profile']['live_body_sources'][name]
    if route['kind']=='local_body':
        value=p
        for key in route['selector']:value=value[key]
        return _body(value),'va'
    if route['kind']!='referenced_body':raise ValueError('Unknown cache facade body source')
    row=p['referenced_bodies'][route['key']];ref=p['references'][row['reference']]
    value=_source((ref['path'],ref['sha256']))
    for key in row['selector']:value=value[key]
    value=_body(value)
    raw=b''.join(bytes.fromhex(i['bytes']) for f in value['fragments'] for i in f['instructions'])
    if hashlib.sha256(raw).hexdigest()!=row['instruction_bytes_sha256']:
        raise ValueError('Cache-facade referenced body differs')
    if row['instruction_address_field'] not in ('va','rva'):raise ValueError('Unknown instruction address domain')
    return value,row['instruction_address_field']


def context_state(base,context,read,*,core_sha256=XP1_CORE_SHA256):
    from .retained_game_source import context_state as game_state
    state=game_state(base,context,read,core_sha256=core_sha256);o=source(core_sha256=core_sha256)['profile']['ownership']
    def q(addr):
        raw=read(addr,8)
        if type(raw) is not bytes or len(raw)!=8:raise ValueError('Incomplete cache-facade identity read')
        return struct.unpack('<Q',raw)[0]
    member=q(state['owner']+o['owner_cache_member_offset'])
    if (not member or q(member)!=base+o['cache_member_vtable_rva']
            or q(member+o['cache_member_owner_offset'])!=state['owner']):
        raise ValueError('Prepared cache member missing, foreign or replaced')
    state.update(member=member,system_member=member+o['system_member_offset'],
        b0_result_owner=member+o['b0_result_owner_offset'],c0_result_owner=member+o['c0_result_owner_offset'])
    return state


def verify_facade_source(backend,context,*,core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import verify_live,SOURCE as selected_source
        if not backend.context_alive():raise RuntimeError('Cache-facade context unavailable')
        verify_live(backend.core_base,backend.read)
        return dict(source_sha256=selected_source[1],identity=context_state(backend.core_base,context,backend.read,core_sha256=core_sha256),full_refresh_admitted=False)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Explicit XP1 facade source required')
    p=source();verify_pinned_files(source_pins());verify_extracted_sources(p['source_pins'].values())
    if not backend.context_alive():raise RuntimeError('Cache-facade context unavailable')
    read=backend.read;base=backend.core_base
    for name in p['profile']['live_body_sources']:
        value,address_field=body(name)
        for f in value['fragments']:
            for i in f['instructions']:
                raw=bytes.fromhex(i['bytes']);address=i[address_field]
                address=int(address,16) if type(address) is str else address
                rva=address-0x180000000 if address_field=='va' else address
                if read(base+rva,len(raw))!=raw:raise ValueError('Cache-facade native instructions differ: '+name)
    for row in p['profile']['targets']:
        raw=read(base+row['vtable_rva']+row['slot'],8)
        if raw!=struct.pack('<Q',base+row['target_rva']):raise ValueError('Cache-facade virtual target differs')
    return dict(source_sha256=SOURCE[1],identity=context_state(base,context,read),full_refresh_admitted=False)


def check_facades(facades,identity,read):
    p=source(core_sha256=facades.abi.core_sha256)['profile'];o=p['ownership'];base=facades.backend.core_base
    rows=(('game_facade','game_facade_vtable_rva','owner'),
          ('cache_service','cache_service_vtable_rva','member'),
          ('system_facade','system_facade_vtable_rva','system_member'),
          ('cache_b0_result','cache_b0_result_vtable_rva','b0_result_owner'),
          ('cache_c0_result','cache_c0_result_vtable_rva','c0_result_owner'))
    for attr,vt,owner in rows:
        ptr=getattr(facades,attr)
        if not ptr:
            if attr.startswith('cache_') and attr.endswith('_result'):continue
            raise ValueError('Required native cache facade missing')
        raw=read(ptr,o['wrapper_size'])
        if type(raw) is not bytes or len(raw)!=32:raise ValueError('Incomplete native cache facade')
        if (struct.unpack_from('<QQQI',raw)!=(base+p[vt],0,identity[owner],1)):
            raise ValueError('Cache facade branch/owner/reference count differs: '+attr)
