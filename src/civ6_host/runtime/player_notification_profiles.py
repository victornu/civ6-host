"""Pinned Player/component query ABIs and actual native owner checks."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from types import MappingProxyType

from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source,_body
from .a0_family_source import A0FamilyProfile,_path,verify_pinned_files,verify_extracted_sources

SOURCE=('work/host-extensions/player-query-static/player-query-xp1-source-v1.json',
        '788b1cbb9199d920ce9e7186f6b6d16a485f8da73c881c6791f06d2ebae77a27')


@dataclass(frozen=True)
class PlayerNotificationABI:
    core_sha256:str
    constants:object


def source():
    p=_source(SOURCE);a=p['profile'];v=p['validation']
    if (p['schema']!='civ6_host.player_query_xp1.static.v1'
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['images']['base']['sha256']!=BASE_CORE_SHA256
            or p['images']['exe']['sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or v['native_execution'] is not False
            or v['all_instruction_bytes_match_pinned_images'] is not True):
        raise ValueError('Player notification source identity differs')
    if (a['wrapper_layout']!={'size':32,'live':8,'cache':16,'refcount':24,
            'initial_refcount':1,'player_component_offset':0x560}
            or (a['event']['kind'],a['event']['record_type'],a['event']['size'])!=(0x20F2116E,0xC1,96)):
        raise ValueError('Player notification ownership or event contract differs')
    return p


def notification_abi(core_sha256):
    from .native import native_player_notifications as original
    names={k for k in vars(original) if k.endswith(('_RVA','_SLOT'))}
    if len(names)!=15:raise ValueError('Player notification constant set changed')
    if core_sha256==BASE_CORE_SHA256:
        values={k:getattr(original,k) for k in names}
    elif core_sha256==XP1_CORE_SHA256:
        raw=source()['profile']['constants']
        values={k:raw[k] for k in names}
    elif core_sha256==XP2_CORE_SHA256:
        from .xp2_player_query_source import source as xp2_source
        raw=xp2_source()['profile']['constants']
        values={k:raw[k] for k in names}
    else:raise ValueError('Unqualified Player notification engine')
    if any(type(v) is not int or v<=0 for v in values.values()):
        raise ValueError('Player notification native address domain differs')
    return PlayerNotificationABI(core_sha256,MappingProxyType(values))


def source_pins(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_player_query_source import source_dependencies
        return source_dependencies()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified Player notification source engine')
    p=source();refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},*p['references'].values(),*p['source_pins'].values()]
    return {str(_path(r['path'])):r['sha256'] for r in refs}


def body(name):
    p=source();route=p['profile']['live_body_sources'][name]
    if route['kind']=='local_body':
        value=p
        for key in route['selector']:value=value[key]
        return _body(value),'va'
    if route['kind']!='referenced_body':raise ValueError('Unknown Player query body source')
    row=p['referenced_bodies'][route['key']];ref=p['references'][row['reference']]
    value=_source((ref['path'],ref['sha256']))
    for key in row['selector']:value=value[key]
    value=_body(value)
    raw=b''.join(bytes.fromhex(i['bytes']) for f in value['fragments'] for i in f['instructions'])
    if hashlib.sha256(raw).hexdigest()!=row['instruction_bytes_sha256']:
        raise ValueError('Player query referenced instructions differ')
    field=row.get('instruction_address_field','va')
    if field not in ('va','rva'):raise ValueError('Unknown Player query instruction address domain')
    return value,field


def context_identity(base,context,read,*,core_sha256=XP1_CORE_SHA256):
    from .retained_game_source import context_state
    return context_state(base,context,read,core_sha256=core_sha256)


def verify_query_live(base,context,read,*,host_pointer,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_player_query_source import verify_live
        result=verify_live(base,read,host_pointer=host_pointer)
        result['identity']=context_identity(base,context,read,core_sha256=core_sha256)
        return result
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified Player notification live engine')
    p=source();verify_pinned_files(source_pins());verify_extracted_sources(p['source_pins'].values())
    for name in p['profile']['live_body_sources']:
        value,field=body(name)
        for f in value['fragments']:
            for i in f['instructions']:
                address=i[field];address=int(address,16) if type(address) is str else address
                rva=address-0x180000000 if field=='va' else address
                raw=bytes.fromhex(i['bytes'])
                if read(base+rva,len(raw))!=raw:raise ValueError('Player query native body differs: '+name)
    a=notification_abi(XP1_CORE_SHA256).constants
    slots=(('PLAYER_MANAGER_VTABLE_RVA','PLAYER_MANAGER_GET_PLAYER_SLOT','PLAYER_MANAGER_GET_PLAYER_RVA'),
           ('PLAYER_VTABLE_RVA','PLAYER_GET_COMPONENT_SLOT','PLAYER_GET_COMPONENT_RVA'),
           ('PLAYER_VTABLE_RVA','PLAYER_RELEASE_SLOT','PLAYER_RELEASE_RVA'),
           ('COMPONENT_VTABLE_RVA','COMPONENT_GETTER_18_SLOT','COMPONENT_GETTER_18_RVA'),
           ('COMPONENT_VTABLE_RVA','COMPONENT_GETTER_10_SLOT','COMPONENT_GETTER_10_RVA'),
           ('COMPONENT_VTABLE_RVA','COMPONENT_RELEASE_SLOT','COMPONENT_RELEASE_RVA'))
    for vt,slot,target in slots:
        if read(base+a[vt]+a[slot],8)!=struct.pack('<Q',base+a[target]):
            raise ValueError('Player query native virtual target differs')
    if read(base+0x9F2640,8)!=struct.pack('<Q',host_pointer):
        raise ValueError('Player query HOST lock receiver differs')
    return dict(source_sha256=SOURCE[1],identity=context_identity(base,context,read),
        positive_loaded_getters_qualified=False)


def _wrapper(read,base,pointer,vt):
    if type(pointer) is not int or pointer<=0:raise ValueError('Missing native Player/component wrapper')
    parts=[]
    # Keep the original helper's bounded eight-byte reader; wrapper padding
    # carries no owner information and is deliberately not interpreted.
    for offset,size in ((0,8),(8,8),(16,8),(24,4)):
        part=read(pointer+offset,size)
        if type(part) is not bytes or len(part)!=size:raise ValueError('Incomplete Player/component wrapper read')
        parts.append(part)
    raw=b''.join(parts)
    actual,live,cache,count=struct.unpack_from('<QQQI',raw)
    if actual!=base+vt or not live or cache or count!=1:
        raise ValueError('Player/component live owner, cache branch or reference count differs')
    return live


def verify_player_wrapper(read,base,player,*,core_sha256=XP1_CORE_SHA256):
    a=notification_abi(core_sha256).constants
    return _wrapper(read,base,player,a['PLAYER_VTABLE_RVA'])


def verify_component_wrapper(read,base,component,player_live,*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_player_query_source import source as selected_source
    elif core_sha256==XP1_CORE_SHA256:selected_source=source
    else:raise ValueError('Unqualified Player component owner engine')
    p=selected_source()['profile'];a=notification_abi(core_sha256).constants
    live=_wrapper(read,base,component,a['COMPONENT_VTABLE_RVA'])
    raw=read(player_live+p['wrapper_layout']['player_component_offset'],8)
    if type(raw) is not bytes or len(raw)!=8 or struct.unpack('<Q',raw)[0]!=live:
        raise ValueError('Player notification component has a foreign or missing owner')


def event_profile(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_player_query_source import source as selected_source, SOURCE as selected_pin
    elif core_sha256==XP1_CORE_SHA256:selected_source,selected_pin=source,SOURCE
    else:raise ValueError('Unqualified Player event engine')
    p=selected_source();verify_pinned_files(source_pins(core_sha256=core_sha256));verify_extracted_sources(p['source_pins'].values())
    from .native.native_deferred_empty_profile import _ROWS
    e=p['profile']['event'];actual=_ROWS.get(e['record_type']);expected=e['receiver_row']
    if (actual is None or set(actual['record_sizes'])!={e['size']}
            or any(actual[k]!=expected[k] for k in ('event_name','handler_va','handler_body_sha256'))):
        raise ValueError('Player notification presentation receiver differs')
    return A0FamilyProfile(MappingProxyType({e['kind']:frozenset((e['record_type'],))}),
        MappingProxyType({e['record_type']:e['size']}),selected_pin[1])
