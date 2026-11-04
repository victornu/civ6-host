"""Pinned XP1 borrowed-event layout, callers and real Session guards."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source,_body,configuration_abi

SOURCE=('work/host-extensions/event-argument-static/event-argument-xp1-source-v1.json',
        'f1a8938b359c23008fa618b309f349268c9ac34d92224fcce79554e355c9922f')


@dataclass(frozen=True)
class EventArgumentABI:
    vtable_rva:int
    successor_rva:int
    count_rva:int


def reader_abi(core_sha256):
    if core_sha256==BASE_CORE_SHA256:return EventArgumentABI(0x81CFA0,0x73B410,0x67370)
    if core_sha256==XP1_CORE_SHA256:
        source()
        return EventArgumentABI(0x93F590,0x83AFA0,0x7FCAA0)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_preload_source import event_reader_source as xp2_source
        a=xp2_source()['event_argument']
        return EventArgumentABI(*(int(a[k],16) for k in
            ('map_vtable_rva','iterator_next_rva','get_count_rva')))
    raise ValueError('Unqualified event argument engine/layout')


def source():
    p=_source(SOURCE)
    from .native.native_absent_scalar_a0 import _EVIDENCE_SHA256
    if (p['schema']!='civ6_host.event_argument_xp1.static.v1'
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['images']['base']['sha256']!=BASE_CORE_SHA256
            or p['images']['exe']['sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or p['references']['absent_scalar_a0']['sha256']!=_EVIDENCE_SHA256
            or p['validation']['all_instruction_bytes_match_pinned_images'] is not True
            or p['validation']['native_execution'] is not False):
        raise ValueError('Event argument source identity differs')
    a=p['profile']
    if (int(a['map_vtable_rva'],16)!=0x93F590 or int(a['iterator_next_rva'],16)!=0x83AFA0
            or int(a['get_count_rva'],16)!=0x7FCAA0 or a['map_size']!=0x58
            or a['map_layout']!={'sentinel':48,'first':56,'root':64,'count':80}
            or a['node_layout']!={'right':0,'left':8,'parent':16,'key':32,'variant':40}
            or a['variant_layout']!={'size':24,'tag':0,'payload':8,'element_count':16,'flags':20}):
        raise ValueError('Event argument map ABI differs')
    expected={'a0_enabled_rva':0x9D3F71,'c0_enabled_rva':0x9D3F72,'session_global_rva':0x9F70A8,
              'session_flag_offset':0,'inner_global_rva':0x9F2620,'inner_session_offset':0x1A60,
              'inner_loading_offset':0x1A70,'host_global_rva':0x9F2640,'internal_enabled_rva':0x9CDDA0}
    if any((int(a['guards'][k],16) if type(a['guards'][k]) is str else a['guards'][k])!=v for k,v in expected.items()):
        raise ValueError('Event argument guard ABI differs')
    for ref in p['references'].values():_source((ref['path'],ref['sha256']))
    return p


def body(name):
    p=source();route=p['profile']['live_body_sources'][name]
    if route['kind']=='local_body':
        value=p
        for key in route['selector']:value=value[key]
        return _body(value)
    if route['kind']!='referenced_body':raise ValueError('Unknown event argument body source')
    row=p['referenced_bodies'][route['key']];ref=p['references'][row['reference']]
    value=_source((ref['path'],ref['sha256']))
    for key in row['selector']:value=value[key]
    value=_body(value)
    raw=b''.join(bytes.fromhex(i['bytes']) for f in value['fragments'] for i in f['instructions'])
    if hashlib.sha256(raw).hexdigest()!=row['instruction_bytes_sha256']:
        raise ValueError('Referenced event argument body differs')
    return value


def _exact(read,addr,size):
    raw=read(addr,size)
    if type(raw) is not bytes or len(raw)!=size:raise ValueError('Incomplete event argument memory read')
    return raw


def _verify_bodies(base,read,names):
    for name in names:
        for f in body(name)['fragments']:
            for i in f['instructions']:
                raw=bytes.fromhex(i['bytes'])
                if _exact(read,base+int(i['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('XP1 event argument instructions differ: '+name)


def verify_reader_live(base,read,*,core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_preload_source import verify_reader
        return verify_reader(base,read)
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Explicit live event reader owner requires XP1')
    abi=reader_abi(core_sha256)
    _verify_bodies(base,read,('iterator_next','get_count'))
    slot=struct.unpack('<Q',_exact(read,base+abi.vtable_rva+0x1D8,8))[0]
    if slot!=base+abi.count_rva:raise ValueError('XP1 event count virtual slot differs')
    return {'source_sha256':SOURCE[1],'live_reader_verified':True,'pointees_copied':False}


def verify_wrappers_live(base,read):
    _verify_bodies(base,read,('a0_existing_map','a0_two_fields','a0_three_fields',
        'event_suppressed','session_getter','session_flag','internal_event_dispatch',
        'prepare','session_factory','session_constructor','session_initialize'))
    return {'source_sha256':SOURCE[1],'a0_wrappers_verified':True,'c0_admitted':False}


def verify_host_live(base,context,read,*,host_pointer,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_preload_source import verify_a0_owner
        return verify_a0_owner(base,context,read,host_pointer=host_pointer)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified A0 owner engine')
    verify_wrappers_live(base,read)
    q=lambda addr:struct.unpack('<Q',_exact(read,addr,8))[0]
    abi=configuration_abi(XP1_CORE_SHA256).load
    if (q(context)!=base+abi.outer_vtable_rva or q(base+0x9F2640)!=host_pointer
            or not q(context+8) or q(context+8)!=q(base+0x9F2620)):
        raise ValueError('XP1 event callback owner/context differs')
    return {'source_sha256':SOURCE[1],'a0_owner_verified':True,'c0_admitted':False,
            'saved_game_load_admitted':False}


def guard_state(base,context,read):
    """Read existing guards only; a dangling post-Destroy global is insufficient."""
    source()
    q=lambda addr:struct.unpack('<Q',_exact(read,addr,8))[0]
    b=lambda addr:_exact(read,addr,1)[0]
    inner=q(context+8)
    if not inner or inner!=q(base+0x9F2620):raise ValueError('Event guard inner context differs')
    session=q(inner+0x1A60);global_session=q(base+0x9F70A8)
    if not session or session!=global_session:raise ValueError('Event guard Session owner is unavailable')
    state={'inner':inner,'session':session,'session_flag':b(session),'loading_flag':b(inner+0x1A70),
           'a0_enabled':b(base+0x9D3F71),'c0_enabled':b(base+0x9D3F72),
           'internal_enabled':b(base+0x9CDDA0)}
    state['a0_open']=bool(state['a0_enabled'] and not state['session_flag'] and not state['loading_flag'])
    return state


def source_pins():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source();refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},*p['references'].values()]
    return {str(resolve_path(resource_root()/r['path'])):r['sha256'] for r in refs}
